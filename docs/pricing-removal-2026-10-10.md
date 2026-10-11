# Pricing (Price Lists) Removal (`rmpricing1`) — 2026-10-10

## Reason

Owner order (2026-10-10), with a screenshot of the admin sidebar entry «لیست‌های قیمت»:

> «هرچیزی مربوط به این ماژول ها هست میخوام پاک کنی کامل پاک کن از کد هیچ اثری نمیخوام ازشون باشه
> برای سایت فروشگاه اینترنتی کارایی ندارن!»

Scope confirmed via follow-up question: **only the price-lists module** (`/admin/pricing`) —
not the rest of the مالی menu group (payments/کارت‌به‌کارت and wallets stay).

## Data check before removal

| Table / row | Live state | What it was |
|---|---|---|
| `price_lists` | 1 row | «همکاران طلایی» — segment GOLD, priority 10, active |
| `price_list_rules` | 1 row | Catalog-wide rule: `min_quantity=0`, `discount_bp=1000` (10%) |
| `customer_segments` | never existed | Only the enum *name* `customer_segment_enum` on `price_lists.segment` (stored as VARCHAR, `native_enum=False`) |
| `permissions` | 2 rows | `pricing:read` (`03d130c4-…`), `pricing:write` (`d64f75a3-…`) — both granted to role `admin` |
| `entity_change_logs` | 0 rows | No `price_list_rule` audit entries ever captured |
| Alembic head before | `rmb2b1` | — |

## What was removed

### Backend

- Whole module `backend/app/modules/pricing/` (12 files):
  - `api/routes.py` — the 3 admin endpoints (`GET/POST /price-lists`, `GET /price-lists/{id}`)
  - `application/pricelist_service.py` — rule resolution engine
  - `application/pricelist_admin_service.py` — admin CRUD
  - `application/pricing_service.py` — the unified engine; its **volume-tier** half moved
  - `application/segment_resolver.py` — loyalty-tier → segment mapping
  - `domain/models.py` — `PriceList`, `PriceListRule`, `CustomerSegment`
  - `schemas/pricing.py` — Pydantic schemas
- `backend/app/main.py` — router spec `("app.modules.pricing.api", "/pricing", ["pricing"])` deleted
  (the spec list fails boot loudly if a spec's module is missing)
- `backend/alembic/env.py` — `import app.modules.pricing.domain.models` deleted
- `backend/app/modules/rbac/application/permission_catalog.py` — `pricing:read` / `pricing:write` catalog entries deleted
- `backend/app/modules/audit/application/change_tracking.py` — `price_list_rule` tracked entity deleted
  (both the `TRACKED_ENTITIES` row and the `register` call — the audit gate requires they leave together)
- `backend/app/modules/cart/application/cart_service.py` — `_resolve_line_price` no longer resolves a
  user segment; `user_id` parameter dropped (all 4 call sites updated)
- `backend/app/modules/checkout/application/checkout_service.py` — `_resolve_buyer_segment` deleted;
  `segment` parameter removed from `_build_line_items` and `_coupon_scope_items`; all 4 call paths
  (quote / validate / create_order / coupon-scope) updated

### Frontend

- `frontend/app/admin/pricing/page.tsx` — the whole page (362 lines) deleted
- `frontend/lib/admin-nav.ts` — nav entry `{ href: "/admin/pricing", label: "لیست‌های قیمت", icon: Tags }`
  deleted from the مالی group, and the now-unused `Tags` icon import removed
  (the bidirectional `admin-nav-reachability.test.ts` requires page + nav entry to leave together)
- `frontend/app/admin/audit/page.tsx` — `price_list_rule: "قاعده قیمت‌گذاری"` display label removed

### Database — migration `rmpricing1`

`backend/alembic/versions/2026_10_10_rmpricing1_remove_pricing_module.py` (down_revision `rmb2b1`):

- Drops `price_list_rules` (child) then `price_lists` (parent), indexes first
- `DELETE FROM permissions WHERE slug IN ('pricing:read', 'pricing:write')` — the admin grants
  cascade with the permission rows
- **Downgrade** recreates both tables with the exact live shape — indexes, FKs, and the
  CHECK constraints with their live double-prefixed names (`ck_price_list_rules_ck_plr_*`; the
  short `ck_plr_*` names are declared so the naming convention produces the live names) —
  re-inserts the live data rows (the «همکاران طلایی» list + its 10% rule, pinned ids) and the
  two permission rows with their **real live ids**, re-granted to the admin role.

## What stayed

- **The volume-tier pricing engine** (`price_tiers`, `calculate_dynamic_price`, `set_price_tier`,
  `list_price_tiers`, `resolve_unit_price`) — the storefront cart/checkout/product page use it.
  It moved from `app.modules.pricing.application.pricing_service` (and the old inventory shim)
  into **`backend/app/modules/inventory/application/pricing_service.py`** as the single real
  implementation, minus the pricelist layering. `resolve_unit_price` now takes no
  `user_segment` / `variant_id`.
- `POST/GET /api/v1/inventory/digital/pricing-tiers` and the digital-inventory tier editor
- `frontend/lib/pricing-tiers.ts` (unused helper, pre-existing dead code — separate question)
- Storefront PDP tier display («قیمت‌گذاری پلکانی») and product-detail price ranges
- Payments (فین‌تک), wallets, discounts — the rest of the مالی menu group
- Historical migration `l4m5n6o7p8q9_add_price_lists_and_rules.py` — it is the alembic chain's
  history; the removal is expressed as `rmpricing1`, per house convention

## Verification

- Backend tests: **387/387 passed** (module had no tests of its own)
- Frontend: **tsc clean**, vitest **79/79 passed** (19 files, including the admin-nav
  reachability test)
- Gates: **9/9 passed** (`run_gates.py`) — ORM↔DB schema sync, endpoint annotations,
  audit capture wired (with `price_list_rule` gone), lazy-relationship, wallet/wishlist gates
- Migration cycle on live DB: `upgrade rmpricing1` → 131→**129 tables**, both tables gone,
  both permissions gone; `downgrade` → both tables restored with **constraint names byte-identical
  to the pre-removal snapshot**, the data row + rule row restored, permissions restored with
  their real ids and admin grants; `upgrade` again → clean
- Fresh chain (`ALEMBIC_SCHEMA` scratch): upgrade head → **129 tables** = live; no
  `price_lists` / `price_list_rules` anywhere
- Live probes: `GET /api/v1/pricing/price-lists` → **404**, `GET /api/v1/pricing/price-lists/{id}`
  → **404**; kept route `GET /api/v1/inventory/digital/products/{id}/pricing-tiers` → 200;
  OpenAPI has **508 paths**, zero `/pricing/` (non-inventory) paths
- Live frontend: `/admin/pricing` → 307 to login (identical to a nonexistent control path);
  login HTML contains zero «لیست‌های قیمت» occurrences
- Negative test (injection protocol): re-adding the nav entry without the page made
  `admin-nav-reachability.test.ts` **fail** (2 failed) — the gate can actually fail; reverted

## Note

- `frontend/.next-watcher/` — a stale generated artifact (08:01, from an earlier session's dev
  server; no live process referenced it) contained a types file for the deleted page and broke
  `tsc --noEmit`. Removed; regenerated on the next run of whatever produced it.
- Pre-existing (not touched, flagged only): `frontend/lib/pricing-tiers.ts` has zero consumers
  (the PDP inlines the same tier-matching logic); `frontend/scripts/verify-admin-nav.mjs`
  asserts 7 nav groups while the nav now has 8 (already stale before this removal).
- Archive: `_archived/pricing-removal-2026-10-10/` (deleted file trees, pre-edit copies of every
  modified file under `_modified/`, `db_snapshot_before.json` with rows + constraint/index/
  permission shapes).
