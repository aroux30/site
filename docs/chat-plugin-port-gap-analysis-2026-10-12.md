# Gap analysis ROUND 2 — plugin vs port (2026-10-12)

Owner: "هنوز قیلی چیزاشو پیاده سازی نکرده — 1001 ناقصه!" (still incomplete).
Round 1 (`chat-plugin-port-gap-analysis-2026-10-11.md`, G1–G13) is CLOSED.
This is a fresh, deeper pass over the full plugin surface (php 1982 lines + 6 JS
files + css), diffed against the port. Every item below was verified by reading
BOTH sides with file:line — not assumed.

Worker: this session (continuing 1001). Watcher: session 1.1.

---

## NEW CONFIRMED GAPS

### N1 — Admin console does NOT render voice notes or attachments (MEDIUM)
- **Plugin** `assets/js/admin-chat.js` `formatContent()` L254–276: turns
  `[Voice Message](url)` → `<audio controls>`; `[Attachment: name](url)` with an
  image ext (jpg/jpeg/png/gif/webp) → inline `<img>` preview; other exts →
  paperclip chip; newlines → `<br>`; bare URLs → clickable links.
- **Port** `frontend/app/admin/chat/page.tsx` `AdminBubble` L542–570: renders
  `{message.message}` as raw text (`whitespace-pre-wrap break-words`). No
  parsing at all → staff see the literal string
  `[Voice Message](https://…/voice.webm)` and `[Attachment: x](…)` instead of a
  player / image / chip. The **widget** side parses these fine
  (`renderMessage` L~560), the admin side does not. Real regression.

### N2 — Admin console has NO notification sound (MEDIUM)
- **Plugin**: `playNotifSound()` (Web Audio beep + optional `sound_url`) fires
  when a new USER message arrives in the active session
  (`admin-chat.js:519`) and when another session's unread total rises
  (`admin-chat-core.js:84–94`).
- **Port** `app/admin/chat/page.tsx`: zero sound code (grep `beep|audio|sound` →
  only the mic `getUserMedia`). Staff never hear a new message. The widget has
  a beep; the console does not.

### N3 — Conversation list: `last_seen_text` + `current_page` are ALWAYS empty (LOW-MED)
- **Plugin** `php:1363`: `current_page = $online->current_page_title`,
  `last_seen_text = format_last_seen($online->last_seen)` (relative time, with
  shamsi/miladi day names).
- **Port** `backend/.../chat_service.py` `list_conversations` L427–428:
  `"last_seen_text": ""`, `"current_page": ""` — hardcoded empty. The frontend
  ALREADY renders both (`page.tsx` L353 `c.current_page`, L356–358
  `c.last_seen_text`) → a **dead UI**: the online row never shows which page the
  visitor is on, the offline row never shows "آخرین بازدید". The presence table
  HAS `page_title` + `last_seen`; the port just never joins them in.
- Sub-part: `date_format` (shamsi/miladi) is stored + has a settings control but
  is never read for the last-seen display (plugin `format_last_seen` L1785).

### N4 — Online-users cards missing UA parse, WP badge, source badges, tabs dropdown (LOW-MED)
- **Plugin** `admin-online.js`: `parseUA()` L5–23 → "دستگاه — مرورگر / OS";
  `is_wp_user` → "WP" badge L92 + "پروفایل WP"/"فرم چت" source badge next to
  phone/email L81/L85; extra-tabs dropdown "🔽 مشاهده N صفحه دیگر" L53–69.
- **Port** `OnlineUsersGrid` L584–648: shows the RAW `user_agent` string, no WP
  badge, no source badges, only `tabs[0]` (no extra-tabs dropdown). Backend
  already sends `is_wp_user` + full `tabs[]` (chat_service L361–366) — the data
  is there, the UI drops it.

### N5 — Widget proactive popup: no dismiss button, no halo/ring animation (LOW)
- **Plugin** `script.js`: the proactive bubble has a close ✕ button (L214,
  L502–506) that dismisses + stamps the cooldown; two expanding halo rings +
  a breathing ring around the launcher (L184–199, L496–497).
- **Port** `floating-chat-widget.tsx` L575–590: the popup is a single button
  that opens the widget — a visitor cannot dismiss it without opening chat; no
  halo/ring animation exists (grep `halo|ring|breath` → 0).

### N6 — Widget: mobile fullscreen window missing (LOW)
- **Plugin** `script.js:218`: on ≤640px the chat window is FULLSCREEN
  (`left:0;right:0;top:0;bottom:0`).
- **Port** L618–619: `min(widget_width, 100vw-2rem)` × `min(widget_height, 100vh-7rem)`
  — stays a floating box on mobile (never fullscreen).

### N7 — Widget: FAQ category count badge missing (LOW)
- **Plugin** `script.js:300`: each category header shows a count chip
  `${g[cat].length}`.
- **Port** FAQ view (`floating-chat-widget.tsx` faqs block): category title only,
  no count badge.

### N8 — Widget: tracking-session auto-promote semantics differ (LOW)
- **Plugin**: the anonymous id used only for presence ("tracking" id) is NOT
  shown in the conversations list; it is auto-promoted into the list the moment
  an admin replies to it (`script.js:960–965`), and the widget jumps to chat.
- **Port** L181–186: the initial key is ALWAYS seeded into the sessions list at
  load → a brand-new visitor already sees an empty "گفتگوی #1" before sending
  anything. Behavioral difference (not a crash), visible to the visitor.

### N9 — Admin console: no per-role message avatars (LOW)
- **Plugin** `admin-chat.js:305–320`: user 👤 / ai 🤖 / admin 👨💼 avatars (or
  configured image) per message row.
- **Port** `AdminBubble`: name label only, no avatar.

---

## VERIFIED NOT-A-GAP (checked, deliberately NOT listing)
- Welcome-view "search FAQs" input: the plugin's is **decorative** — it has NO
  input handler (grep: placeholder + icon only). Port omitting it is fine.
- `custom_sound_url`: documented deliberate drop (Web Audio beep) — already
  known; owner may still want it back (flag only, not a bug).
- Dark mode (G13), RTL anchor (F10), webhook hardening (F1–F4) — closed in
  round 1; re-confirmed present.

---

## STATUS
Sent to watcher (1.1) for review before implementing. Severity order for
implementation: N1, N2, N3, N4 first (real user/staff-visible), then N5–N9.
