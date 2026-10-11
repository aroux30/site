# RTL admin-table mobile overflow fix (2026-10-06)

## What was reported

Every admin page with a wide `DataTable` had a pre-existing horizontal page
overflow on mobile: `document.documentElement.scrollWidth` was 574 instead of
390 at a 390px viewport. The handoff attributed this to the table's min-content
width propagating through RTL scroll geometry, and prescribed the canonical
dir-swap fix (`dir="ltr"` on the scroller + `dir="rtl"` on the table).

## What live measurement actually found

The prescribed fix did work when measured live (dashboard 574 → 390), but it
was not the real mechanism — and it needed a scrollLeft pin because after the
swap `scrollLeft=0` shows the table's **end** columns (measured: `scrollLeft=0`
shows اقدام/عملیات; `scrollLeft=max` shows شماره سفارش).

The actual mechanism, established by attribution probes on the live DOM:

- The table **was always contained** by its `overflow-x-auto` scroller and
  scrolled fine internally.
- The document growth came from the `sr-only` spans in action-column headers
  (`<span className="sr-only">عملیات</span>` — dashboard, products, orders,
  users, categories, tickets). They are `position:absolute`; with **no
  positioned ancestor** their containing block is the **viewport**, so the
  scroller's clip does not apply to them, and in RTL they extend the
  document's scrollable overflow to the left.
- Proof: document growth equaled the span's offset exactly (dashboard −184 →
  +184px, products −160 → +160, orders −456 → +456, users −415 → +415).
  Removing only those spans restored 390; adding `position:relative` to the
  scroller (making it their containing block) also restored 390.

## The fix

One class, no JS, native RTL scroll semantics preserved:

- `frontend/components/admin/data-table.tsx:217` — `relative overflow-x-auto`
  on the scroller (with an 8-line comment explaining why `relative` is
  load-bearing).
- `frontend/app/admin/users/page.tsx:650` — `flex-wrap` on the filter row
  (a second, independent +71px leak: the "کاربر جدید" button row).
- Same `flex-wrap` pattern applied to five more measured pages:
  `rbac` (509→390), `email-templates` (479→390), `reports` (403→390),
  `digital-inventory` (532→390), `gamification` (397→390).

The dir-swap alternative was measured equivalent in outcome on all affected
pages; containment won on simplicity (no JS, no scrollLeft pin, no load-time
flash of end columns, no change to scroll semantics for other sessions).

## Verification (all live, real Chromium, real admin login)

- **Acceptance pages at 390px** — `scrollWidth === 390` on dashboard (574→390),
  products (550→390), orders (846→390), users (805→390), plus categories
  (421→390) and tickets (479→390). Internal scrolling verified working
  (RTL scrollers scroll 0 → −max; end columns come into view; document stays
  390 throughout). Initial view shows the first column without any scroll.
- **Full sweep** — 45 admin routes at 390px: 38 at 390 (was 33). Before/after
  in `%TEMP%/rtl-probe/{baseline,postfix}/report.json`.
- **Negative test** — sabotaging the fix in the DOM (`relative` → `static`)
  restores the exact original numbers (dashboard 574, users 805); restoring
  the class returns 390. The acceptance check can genuinely fail.
- **Dialogs** — orders and kanban detail dialogs open at 390 with their
  line-item tables contained (`overflow-hidden` wrappers, no leaks).
- **Static** — `npx vitest run` 24/24; `npx tsc --noEmit` clean.
- **Cross-server** — confirmed on both the canonical :3000 dev server and the
  isolated :3100 preview server.
- Zero console/page errors on all 11 touched pages.

## Remaining overflows (documented, NOT table-related)

7 routes still overflow; none are caused by tables and none are reachable by
the patterns used here:

| Route | sw | Cause |
| --- | --- | --- |
| /admin/blog, /admin/cms, /admin/pages, /admin/redirects, /admin/seo, /admin/settings | 421 | Admin layout header cluster (`app/admin/layout.tsx`, header right-side controls overflow by 31px). Off-limits in this task; fix belongs to the layout owner. |
| /admin/media | 633 | Folder-tree + asset-grid layout (`div.flex.gap-4` row). `min-w-0` on the chain and outer `flex-wrap` were tested and are insufficient (594 remains); needs real layout work. |

## Files touched

`components/admin/data-table.tsx`, `app/admin/users/page.tsx`,
`app/admin/rbac/page.tsx`, `app/admin/email-templates/page.tsx`,
`app/admin/reports/page.tsx`, `app/admin/digital-inventory/page.tsx`,
`app/admin/gamification/page.tsx`. Nothing else — `app/admin/layout.tsx`,
`lib/admin-nav.ts`, `components/admin/admin-nav.tsx` were explicitly off-limits
and are untouched.

Probe scripts: `%TEMP%/rtl-probe/` (probe, attribution, precision, bisect,
sweep, acceptance2, postfix).
