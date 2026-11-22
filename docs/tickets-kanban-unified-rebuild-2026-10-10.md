# Tickets: unified page + board — and the orders drag-lag fix — 2026-10-10

Owner order: apply the same treatment to tickets/support that orders got —
one page with list/board views, rebuilt UI, real drag & drop — and fix the
reported drag lag on the orders board (verified E2E with Playwright).

## 1. Orders drag lag — root causes (measured, not guessed)

Tooling: Playwright + PerformanceObserver (`longtask`) + rAF frame counter +
CDP CPU profiler, against both the dev server and a production build.

**Before:** 8 long tasks totalling 2,432ms (worst 1,041ms), 0 animation
frames during a 6.4s drag — i.e. the main thread was blocked in slices.

Three causes, each fixed and re-measured:

1. **`useSortable` on every card.** It re-measures every registered item
   and re-renders every subscriber on each pointer move, and the board has
   NO intra-column ordering (the server always returns created_at desc), so
   the sortable machinery was pure cost. Cards are now plain `useDraggable`
   (only the active card re-renders).
2. **dnd-kit context churn re-rendered all ~200 cards.** Context updates
   bypass `memo`, so every collision-target change re-rendered the full
   card markup. The context subscription now lives in a cheap shell
   component; the expensive body is a separate memoized component with
   stable props (columns too, with ref-stable callbacks).
3. **`new Intl.NumberFormat` per call.** The CPU profile showed 102ms of
   self time in `formatPrice` alone; `toPersianDigits` also allocated its
   digit table per call. Both are now module-level singletons.

**After (dev):** 2 long tasks totalling 256ms (worst 155ms), 57fps.
**After (production build):** 2 long tasks totalling 218ms (worst 120ms),
57fps, 1 frame gap > 100ms. A ~9.5× reduction in blocked main-thread time.

**Bonus bug found by the same instrumentation:** `closestCorners` collision
detection was resolving drops to the WRONG column — a drag released over
«تایید شده» resolved to «در حال بسته‌بندی» (instrumented drag:
`over=status:packing` while the cursor was over confirmed). Cause: columns
have wildly different heights (a 50-card lane is ~11,000px tall, a short
one ~500px), and closestCorners scores by average corner distance — which
prefers the short column. This is also why the user experienced "drag does
nothing": the resolved target was an illegal transition, so the refusal
path ran and the card snapped back. Replaced with `pointerWithin` +
`rectIntersection` fallback (source lane excluded for keyboard drags).

Keyboard drag (Space/arrows/Space) re-verified working end-to-end: 1 real
PATCH after crossing into the adjacent column.

## 2. Tickets: what shipped

**One page** — `/admin/tickets` with a view switch (لیست / کانبان), view in
`?view=board`. No second nav entry existed (tickets was always one entry),
so the menu is unchanged; the old 104-line list and 260-line detail page
were replaced by the shared list/board/drawer components.

**Board** — 5 columns (open / in_progress / waiting / resolved / closed),
real drag & drop via the same architecture as orders (plain draggables,
pointer-first collision, memoized columns, optimistic move + rollback).
Ticket statuses have NO backend state machine (`PATCH` accepts anything),
so the transition table in `ticket-domain.ts` is a UI guard rail — a drag
cannot jump a ticket from «باز» straight to «بسته‌شده» by accident.

**Drawer** — the conversation surface: customer identity, thread with
staff/customer bubbles, legal-transition buttons, and a reply composer
(hidden for closed tickets — the backend refuses messages on closed
tickets, so the old page's always-visible form surfaced a generic error
after submit).

**Backend additions:**
- `GET /support/admin/tickets/stats` — zero-filled per-status counts +
  `urgent_open` + `unassigned` (registered BEFORE `/{ticket_id}`; a test
  pins the order and was negative-tested by swapping the routes).
- Admin list rows now carry `customer_name` (from the profile — NOT
  `user.first_name`, which does not exist; the same bug class the orders
  admin had), `customer_phone`, `messages_count`, `last_message_preview`.
- `search` (number/subject) and `priority` filters, server-side.
- Admin detail payload carries customer identity (the old detail page
  rendered a raw user UUID).

## 3. Live bugs found and fixed on the way

1. **Tickets list rendered raw user UUIDs** — no name, no phone, no way to
   tell who was writing. Now: profile name + phone on every row.
2. **Search filtered only the current page** (client-side over 20 rows).
   Now server-side (`ticket_number ILIKE` or `subject ILIKE`).
3. **No priority filter existed at all** — urgent tickets were findable
   only by scrolling. Now: priority chips (list) + an urgent-open counter
   (board toolbar).
4. **Reply form shown on closed tickets** — guaranteed server rejection.
   Now hidden with an explanation.
5. **A parallel session left `app/(store)/login/layout.tsx` with duplicated
   imports** (lines 3-4 and 6-7 identical), which 500'd the login page and
   with it every unauthenticated redirect path. Fixed; scanned the rest of
   `app/` for the same pattern (none found).

## 4. Gates added

Frontend (`frontend/tests/ticket-board-logic.test.ts`, 12 tests):
- status/priority visual coverage, unique labels
- transition invariants: known targets, no self-loops, closed reopens only
  to open, every status reachable from open (BFS), advance steps legal
- staleness: fires only for active tickets past 48h; resolved/closed never
- relative-time buckets; unparsable dates never alarm

Backend (`backend/app/tests/unit/test_admin_ticket_board.py`, 5 tests):
- route order stats-before-{id} (negative-tested: swap fails)
- live stats zero-fill + totals consistency
- enrichment attaches identity/thread keys, previews truncated to 120 chars
- empty input → empty output (no fabricated rows)
- detail payload carries customer fields

Existing suites re-run green: backend full unit suite, frontend 114 tests
(22 files), `tsc --noEmit` clean.

## 5. Verification evidence (Playwright, live server, real admin session)

Orders board:
- legal drag → 1 PATCH + success toast; illegal drag → **0 PATCH** + refusal
- keyboard drag → 1 PATCH; advance button → 1 PATCH; 0 console errors
- perf: see §1 numbers; screenshots `docs/orders-*.png`

Tickets page:
- list: 2 rows, status + priority chips, customer name/phone/msg count
- board: 5 columns, header badges match the stats endpoint exactly
  (verified against the API: open=0, in_progress=1, closed=1, total=2)
- legal drag waiting→in_progress: 1 PATCH + toast + badges resync
- drag perf: **60fps, 0 long tasks, worst frame gap 17ms**
- drawer: customer identity, thread, transitions, reply form all present;
  transition from the drawer updates the board
- `/admin/kanban` still redirects to `/admin/orders?view=board`
- 0 console/page errors across all runs; screenshots `docs/tickets-*.png`

## 6. Files

New (frontend):
- `lib/admin/ticket-domain.ts` — statuses, UI-policy transitions, visuals,
  staleness, relative time
- `components/admin/tickets/{tickets-board,ticket-board-column,ticket-board-card,tickets-list-view,ticket-detail-sheet}.tsx`
- `tests/ticket-board-logic.test.ts`

Rewritten: `app/admin/tickets/page.tsx` (was a 104-line table-only page),
`app/admin/tickets/[id]/page.tsx` (identity instead of UUID).
Touched: `lib/api/tickets.ts` (stats + filters + row extras).

Orders perf fix: `components/admin/orders/order-board-card.tsx` (shell/body
split), `order-board-column.tsx` (memo + card-list memo), `orders-board.tsx`
(pointerWithin collision, stable callbacks), `lib/utils.ts` (cached
formatter/digits).

New (backend): stats service + enrichment (`support_service.py`), routes,
schemas; `tests/unit/test_admin_ticket_board.py`.
