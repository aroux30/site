# Orders + Kanban: unified page, rebuilt board — 2026-10-10

Owner order: the two entries («سفارش‌ها» and «میز کانبان سفارشات») must become
ONE menu and ONE page with a list/board view switch; both views rebuilt from
scratch (the old UI was rejected outright), and the board must have real drag &
drop. Eight reference repositories were studied first (see §5).

## 1. What shipped

**One page** — `/admin/orders` with a view switch (لیست / کانبان). The view is
persisted in `?view=board` and localStorage. `/admin/kanban` is now a redirect
to `/admin/orders?view=board` (bookmarks keep working). The sidebar lost the
duplicate entry.

**Real drag & drop** on the board via `@dnd-kit/core@6.3.1` +
`@dnd-kit/sortable@10.0.0` (React 19 compatible; react-beautiful-dnd — used by
most of the reference repos — is deprecated and incompatible with React 19).

The drag contract, all four rules enforced:
1. Only state-machine-legal transitions accept a drop (mirrored table, gated by
   a parity test against the Python source). Illegal targets show a red ring
   and refuse with a toast — **zero requests** (verified: PATCH count = 0).
2. Legal drops apply optimistically, then PATCH, then resync the two affected
   columns + header stats.
3. Server failure rolls the optimistic move back with the reason shown.
4. Same-column drops are ignored (no manual ordering exists server-side).

Keyboard drag works (dnd-kit KeyboardSensor on a dedicated grip button):
Space lifts, arrows move, Space drops — verified end-to-end (1 real PATCH).

**Board data model** — each column fetches its own page (`status=X&page_size=50`,
«نمایش بیشتر» for more). Column HEADER numbers come from a new whole-table
stats endpoint, so a 24,682-row lane reads its real count, not the page size.

**Detail drawer** (side sheet) — loads the new admin detail endpoint: unmasked
address, real payment rows, timeline, and ONLY the legal transitions as buttons.

## 2. New backend surface

- `GET /orders/admin/orders/stats` — per-status counts + sums (zero-filled over
  the full enum), total orders, revenue excluding canceled/refunded. Registered
  BEFORE `/{order_id}` (the GET twin of the documented bulk-status route trap;
  a test pins the registration order).
- `GET /orders/admin/orders/{id}` — `AdminOrderDetailResponse`: unmasked address
  snapshot, payments, timeline, customer name/phone. Standalone schema (NOT
  inheriting `OrderResponse`) so the customer masking validator cannot apply —
  a test asserts the returned address is not masked.

## 3. Live bugs found and fixed along the way

1. **Customer name was ALWAYS null on every admin surface.**
   `enrich_admin_order_rows` read `user.first_name` / `user.last_name` —
   attributes `User` does not have (names live on the joined `profile`).
   Verified against live data: 18 profiles carry names; not one reached the
   field. Fixed to read the profile (+ `display_name` fallback).
2. **Pager read a field that does not exist.** The old list read
   `meta.total`; the backend sends `meta.total_items` — every pager said
   "0 از 0". The new client reads `total_items`.
3. **Fabricated "پرداخت شده" on the board.** The list endpoint carries no
   payment field; the old kanban defaulted every order to paid. Payment status
   is now derived only from real payment rows (drawer), and the list shows the
   honest "بدون اطلاعات پرداخت".
4. **Five statuses were invisible on the old board.** Its column set omitted
   `on_hold`, `completed`, `returned`, `refunded`, `partially_refunded` — an
   order in one of those states appeared in no column while still counting in
   totals. The new board surfaces `on_hold` as a card badge and the drawer
   covers every status; a test pins "every status is either a column or
   explicitly off-board".
5. **The old table's status Select offered illegal transitions.** It listed six
   statuses from every state; the server rejected most choices after the click.
   Transitions now live in the drawer (legal moves only) and on the board.

## 4. Honesty decisions (deliberate, documented)

- **Refund transitions are NOT buttons in the drawer.** PATCH to
  `refunded`/`partially_refunded` flips the STATUS only — the money moves
  through `POST /payments/{id}/refund` (`payments:refund`). Offering them as
  plain buttons would print «بازگشت وجه کامل» with no refund issued. The
  drawer explains this and points to the payments surface.
- **Bulk cancellation is offered WITH the consequence text** (restock + wallet
  refund) in the confirm dialog, and a partial run is reported as partial with
  per-order reasons kept on screen.
- **Stale = 24h since order creation** for pending/confirmed/processing/on_hold
  — the banner now says «از ثبت سفارش», not «در این مرحله» (the old wording
  was wrong about what was measured).

## 5. Reference repositories studied (8)

| repo | DnD | verdict |
|---|---|---|
| themesberg/flowbite-react-admin-dashboard | SortableJS (Pro only) | public repo has NO kanban; Pro is a mockup, no persistence |
| marmelab/atomic-crm | @hello-pangea/dnd | best patterns: config-driven stages, optimistic move + refetch (no rollback — we added it), column aggregate |
| braiekhazem/react-kanban-kit | pragmatic-drag-and-drop | domain-shaped move payload, closest-edge indicator; beta, no a11y, no RTL |
| asseinfo/react-kanban | react-beautiful-dnd | archived 2022, React-19-incompatible; only its pure board-transformer helpers are worth reading |
| JohannesL2/kanban-board | @dnd-kit | closest to what we built: nested SortableContext, TouchSensor activation distance, separate keyboard grip |
| chamatt/KanbanBoard | react-beautiful-dnd | rbd keyboard announcements for free; else minimal |
| leriuz/react-kanban-board | native HTML5 | teaching demo; the flat-model + persist-wrapper pattern only |
| jonatakuzi/react-kanban | native HTML5 | single-file demo, nothing to adopt |

**Decision: @dnd-kit.** It is the only stack in the set that is maintained,
React-19 compatible, RTL-safe (sensors are direction-agnostic; column order is
DOM order under `dir="rtl"`), and ships a keyboard sensor + announcements.

## 6. Gates added (all able to fail)

Frontend (`frontend/tests/`):
- `order-status-parity.test.ts` — parses `_VALID_TRANSITIONS` and
  `_CUSTOMER_CANCELABLE` from the Python source (CRLF-normalized) and fails on
  any drift. Negative-tested: an injected fake transition fails with the
  mismatch named.
- `order-board-logic.test.ts` — board coverage of every status, advance-button
  legality (never skips a stage, never on terminal), payment derivation (never
  invents "paid"), staleness windows, money conversion.

Backend (`backend/app/tests/unit/test_admin_order_board.py`):
- route registration order (negative-tested by swapping: fails)
- admin detail schema does not inherit the masking customer schema
- live-DB: stats zero-fill + totals consistency; detail returns unmasked address
- missing order raises NotFoundError

Existing gates updated: `admin-nav-reachability.test.ts` — `/admin/kanban` moved
to UNLINKED_BY_DESIGN with its redirect reason.

## 7. Verification evidence

- Frontend: `tsc --noEmit` clean; 102 tests pass (21 files).
- Backend: full unit suite passes; new 5 tests pass.
- Live (Playwright against the dev server with a real admin session):
  - board renders 7 columns, 201 cards; header badge ۲۴٬۶۸۲ (real count)
  - real drag pending→confirmed: toast + PATCH + counts moved 24682→24681 /
    2057→2058
  - illegal drag pending→delivered: red ring, refusal toast, **0 PATCH calls**
  - keyboard drag: Space/Arrow/Space produced 1 real PATCH
  - drawer: opens, shows unmasked-address section, payments, timeline; refund
    buttons absent, explanation shown
  - bulk selection: 3 rows selected, action bar with 5 statuses + cancel
  - 0 console/page errors across all runs
- Screenshots: `docs/orders-*.png`.

## 8. Files

New:
- `frontend/lib/admin/order-domain.ts` — status enum, mirrored transitions,
  visuals, payment derivation, staleness, money (one source for both views)
- `frontend/lib/api/admin-orders.ts` — typed client for the 5 endpoints
- `frontend/lib/hooks/use-debounced-value.ts`
- `frontend/components/admin/orders/{orders-board,order-board-column,order-board-card,orders-list-view,order-detail-sheet}.tsx`
- `backend` schemas/service/routes additions; `test_admin_order_board.py`

Rewritten: `frontend/app/admin/orders/page.tsx` (was 988-line table-only),
`frontend/app/admin/kanban/page.tsx` (was 1203-line board; now a redirect).

Removed: the duplicate nav entry in `frontend/lib/admin-nav.ts`.
