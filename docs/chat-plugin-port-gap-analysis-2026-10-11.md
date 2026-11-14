# Gap analysis — WordPress plugin (chat-bot) vs ported chat module

**Date:** 2026-10-11 (owner reported "1001 ناقصه" — the port is incomplete)
**Plugin:** `C:\Users\Administrator\Desktop\chat-bot\n8n-custom-chat.php` (1982 lines) + assets JS
**Port:** `backend/app/modules/chat/` + `frontend/components/chat/` + `frontend/app/admin/chat/`

Every finding below was verified by reading BOTH sides (grep + source reads), not
assumed. Items marked ✅ are genuinely ported; ❌ are gaps.

---

## CONFIRMED GAPS (need implementation)

### G1 — User message NOT forwarded to Telegram during handoff (HIGH)
Plugin `n8n_chat_send` (php:1104-1123): when `handoff_until > now`, the user's
message is forwarded to the session's Telegram topic:
`send_to_telegram("👤 <b>پیام کاربر:</b>\n{msg}\n\nشناسه: <code>{sid}</code>", $thread_id)`.
Port `send_message` (routes.py:164-190): only skips the n8n call when
`handoff_active` — sends NOTHING to Telegram. **The operator never sees the
visitor's messages during a live human handoff** — the core promise of the
feature. Also: the plugin sends user messages to Telegram only during
handoff; the port must add the same forward in the handoff branch.

### G2 — Flow completion does not save individual messages (MEDIUM)
Plugin `n8n_chat_flow_complete` (php:1137-1187): saves EACH flow entry to the
DB (role user/ai/admin), returns `saved_ids`+`last_id`; the transcript sent to
n8n is separate. Port: no `flow_complete` route exists; `doSend("", finalCtx)`
just posts the joined summary as ONE user message (widget L372-392). Result:
after a flow, the visitor's chat history shows one wall-of-text summary
instead of the individual Q/A bubbles; reload loses the flow structure.
(Plugin parity note: also has a 5s idempotency lock — port has none.)

### G3 — Multi-session "conversations" tab missing (MEDIUM)
Plugin widget: welcome tab + **conversations tab** listing all sessions from
`localStorage.n8n_chat_sessions` (numbered, per-session unread dots, "شروع
گفتگوی جدید", switch between sessions; js:257-275, 351-427). Port widget:
single `SESSION_KEY` (`chat_session_key`), no session list, no switching.
A returning visitor cannot see or resume older conversations.

### G4 — Quick replies (legacy mode) not rendered (LOW-MEDIUM)
Plugin: `quick_replies` newline list → 2-col button grid shown when no user
message exists yet (js:837-902). Port: key exists in config + schema but the
widget never renders it (0 hits). The port built the tree builder (quick_flow)
but dropped the simpler sibling feature.

### G5 — Emoji picker missing (LOW-MEDIUM)
Plugin: ~160-emoji picker in the composer (both widget js:321-347 and admin
console). Port: 0 hits in either. Visitors/staff lose quick emoji insertion.

### G6 — Admin console voice notes missing (MEDIUM)
Plugin admin: mic button + MediaRecorder + voice UI (admin-chat.js:391-444),
uploads as `admin_voice_{ts}.webm`. Port admin console: no MediaRecorder
(0 hits) — staff cannot send voice replies (the widget side HAS voice).

### G7 — Multi-tab beep guard missing (LOW)
Plugin: `localStorage.n8n_last_beep` 3s window prevents every tab beeping
(js:66-80). Port: no guard — with several storefront tabs open, each beeps.

### G8 — Logged-in user identity not synced from server session (MEDIUM)
Plugin heartbeat (php:1609-1687): for a logged-in user it reads the WP session
(display_name/email — TRUSTED SOURCE), syncs sessions table, and only falls
back to the JS hint (and only upgrades guest names). Port heartbeat
(routes.py:285-298): uses `session.user_name` from the DB only; never derives
identity from the authenticated `user` (which it already has via
`get_current_user_optional`). Result: a logged-in visitor's real name/email
never lands on the session; online-users cards show "مهمان" for logged-in users.

### G9 — Online-users cards: no phone/email, no WP-profile source (LOW-MEDIUM)
Plugin `admin_get_online_users` (php:1700-1777): phone/email resolved from the
**WP user profile** (billing_phone → user_phone → phone meta), with a source
badge (پروفایل WP vs فرم چت), plus `is_wp_user`. Port `online_users`
(chat_service.py:286-316): `user_phone`/`user_email` hardcoded `""` and never
filled. The `online_show_fields` allow-list exists in config but the data
behind two of its three fields is always empty.

### G10 — `?session=` deep-link into the admin console missing (LOW)
Plugin: URL param `?session=` auto-opens that conversation (admin-chat.js:613-622);
the online-users "ارسال پیام" button links there. Port: no searchParams
handling (0 hits) — the console cannot be linked to a specific conversation.

### G11 — Proactive popup: `{page_title}` placeholder not substituted (LOW)
Plugin replaces `{page_title}` in `proactive_text` with `document.title`
(js:494). Port: 0 hits — the popup shows the literal `{page_title}` text if
an operator uses it. Verified: the only `page_title` in the widget is the
heartbeat payload field (L221), a different thing.

### G12 — Pre-chat `textarea` field type renders as an invalid input (LOW)
Plugin renders `<textarea>` for `field_type=textarea` (js:277-291). Port
renders `<input type={f.type || "text"}>` (L700) — a `textarea` type produces
`<input type="textarea">`, which browsers fall back to a plain text input.
Multi-line pre-chat answers become single-line.

### G13 — Dark mode missing in the widget (NICE-TO-HAVE)
Plugin has `prefers-color-scheme: dark` variables for the whole widget
(js:153-164). Port: 0 `dark:` hits. On a dark-themed OS the widget stays light
(acceptable, but a visible difference from the plugin).

---

## VERIFIED AS ALREADY PORTED (no action)

- Welcome/FAQ/news tabs ✅ (with CMS fallback — an improvement)
- Quick flow tree (render + admin builder) ✅
- Pre-chat form builder + validation ✅ (types text/email/tel/number — the
  `textarea` type is G12 above)
- Voice notes (widget) + file attach (both sides) ✅
- Unread badge, read receipts (✓/✓✓), sound (Web Audio beep) ✅
- Handoff (request + system msg + countdown + TG topic notify + reply ingest +
  inline delete button + webhook secret hardening — port is STRICTER) ✅
- n8n request shape + response parsing variants + handoff mute ✅
- Admin: conversations list (online-first, unread, last msg, time-ago),
  thread (sender badges, ticks), composer (attach/emoji-picker→MISSING),
  session info panel, delete (with TG topic sync), online users tab
  (grouped, tabs dropdown, WP badge), handoff toggle ✅ (except G6/G9/G10)
- Cleanup cron (daily, auto_delete_days) ✅
- Colors ×5, positioning offsets ×4, avatars ×4, widget icon, RTL ✅
  (dark mode: port has none — plugin has prefers-color-scheme CSS; NICE-TO-HAVE)
- Config masking of secrets ✅ (port improvement over plain-text plugin)

## NOTES (not gaps, for awareness)

- Plugin has NO rate limiting and two admin AJAX endpoints without nonce/cap
  checks (`admin_get_conversations`, `admin_poll_messages`); the port is
  stricter everywhere (rate limits + RequirePermissions). Do NOT copy those.
- Plugin `custom_sound_url` (MP3 upload): port documented as deliberately
  dropped (built-in beep). Owner may want the upload back — flag only.
- Plugin date_format shamsi/miladi for "last seen": port uses its own date
  system; verify the admin console time-ago matches expectations.
