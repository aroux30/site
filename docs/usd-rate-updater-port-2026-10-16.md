# USD→Toman price updater (Nobitex) — port report

Date: 2026-10-16
Source: the owner's WordPress plugin `AROUX-Currency-Updater`
("Nobitex Price Updater Ultimate" v4.5.0)
Target: this project (FastAPI + Next.js admin)

## What the plugin did

- A WP-cron job fetched the USDT/IRT last-trade price from the Nobitex API
  every N minutes (`nobitex_update_interval`).
- It walked every WooCommerce product and variation that carried a
  `_usd_price` meta value, and rewrote the Toman price as
  `round(usd_price × rate)` with a rounding step (`nobitex_price_rounding`).
- With `_usd_sale_price` present, the sale price was charged and the base
  became the regular price.
- Admin page: settings (API on/off, manual fallback rate, interval,
  rounding), status panel (current rate, last update, next run), a manual
  "update now" button, and a log viewer with clear/download.
- A rotating text log (`logs/nobitex_price_updates.log`, 5 MB cap, 5 files).

## What the port contains

Backend — new module `backend/app/modules/currency/`:

| File | Contents |
|---|---|
| `domain/models.py` | `usd_price_updates` table — one row per sweep (rate, source, count, scheduled/manual, status, error, per-variant detail as JSONB) |
| `application/rate_config.py` | One `SiteSetting` row `currency.usd_rate`; defaults, clamping, server-owned `last_*` fields, `is_due`, `next_run_at` |
| `application/nobitex_client.py` | Two-endpoint client: order book (plugin parity) → market stats (live fallback); sanity window |
| `application/price_update_service.py` | `run_price_update` — rate resolution, variant rewrite, outbox events, cache bust, history row, runtime state |
| `application/rate_history.py` | History filters + CSV export (reporting builder, 50k cap) |
| `application/tasks.py` | Celery task, one beat tick per minute, interval-gated inside the task |
| `api/routes.py` | `GET/PUT /admin/currency/config`, `POST /admin/currency/update-now`, `GET /admin/currency/history`, `GET /admin/currency/history/export.csv` |

Catalog changes:

- `product_variants.usd_price` / `usd_sale_price` — `NUMERIC(12,2)`, nullable.
  `NULL` = not managed by the sweep. Partial index on `usd_price IS NOT NULL`.
- `VariantCreate` / `VariantUpdate` / `VariantResponse` carry the two fields;
  `0` clears (the existing nullable-price convention).
- Nested product create and variant update both persist them.
- Audit registry (`change_tracking.TRACKED_ENTITIES["variant"].fields`) now
  captures `usd_price` and `usd_sale_price`.

Migration: `curr1` (revises `refbon2`). Additive only — every existing
variant starts with NULL USD prices, so installing changes no price.

Admin UI:

- `/admin/currency` — two tabs: settings (status card + form + "update now")
  and history (filterable, searchable, server-paginated table with CSV
  export and a per-variant change-detail dialog).
- Nav entry under فروشگاه: «به‌روزرسانی قیمت دلاری».
- Product editor modal: USD base / sale inputs with a two-decimal keystroke
  gate; empty = not managed. On edit the values go to the first variant
  (`PATCH /catalog/variants/{id}`); on create they ride the nested variant.
- Permissions: `currency:read`, `currency:write` (seeded to the admin role
  at boot).

## Deliberate differences from the plugin

| Plugin behaviour | Ported behaviour | Why |
|---|---|---|
| Manual rate default 50000 Toman | default 0 (= unset) | A stale 50000 would silently halve every price in a much higher market |
| `log_enabled` off stopped price updates entirely | off only stops history rows | The switch was documented as logging; making it kill pricing was a trap |
| Log file inside the plugin dir | database table | Queryable, filterable, exportable; survives redeploy; read-only filesystems |
| Products saved one by one | one transaction per sweep | A crash left half the catalog on the old rate |
| Every managed product re-saved each run | only CHANGED prices written | Avoids audit-row and search-event churn per run |
| Whatever the API returned was written | sanity window (1,000–100,000,000 Rial) | `lastTradePrice: 0` would have zeroed the catalog |
| Single endpoint (order book) | order book → market stats fallback | Measured live: the order book endpoint answers 403 to non-browser clients from some networks while market stats answers 200 with the same value |
| No search/cache consequence | ProductUpdated outbox event + slug-cache delete per changed product | ES sort/filter by price must track; the 300 s product cache must not serve dead prices |

## Verification performed

Backend (547 tests, all passing; +18 new in
`tests/unit/test_currency_usd_updater.py`):

- Nobitex payload parsing: string/numeric forms; zero/negative/absurd/hostile
  bodies refused; fallback chain order (order book 403 → stats 200; order
  book 200 → stats never called; both down → None).
- Rounding: the plugin's own worked example (111,612 Toman with step 200 →
  111,600).
- Config: defaults, clamping, server-owned refusal, server-owned write path
  guarded by exact expression, `is_due` truth table incl. failed attempts and
  disabled state.
- Wiring pins: celery beat + TASK_MODULES, main.py mount line, permission
  catalog, NUMERIC-not-float column declaration, audit fields, the
  log-switch-placement structural pin (verified to FAIL under an injected
  plugin-shaped early return), and the 0-clears-USD variant update.

Live E2E (`scripts/verify_usd_rate_updater.py`, ends
"ALL E2E STEPS PASSED"):

- Real admin cookie login; scratch product created with USD 9.99/7.99;
  pinned manual rate 987,654 Rial and rounding 200 Toman.
- Sweep produced price=789,200 / compare=986,600 Toman — exact expected
  values, asserted.
- A second run is a no-op (updated_count=0) and is still logged.
- History list, SKU free-text search, and the BOM'd CSV export all verified.
- Server-owned `last_rate_rial` sent in the config PUT is ignored.
- Original config restored; scratch product and history rows deleted by
  exact primary key (never pattern deletes).

Live E2E with the REAL Nobitex rate (API on): rate 2,654,710 Rial (265,471
Toman) fetched through the fallback endpoint; a 10.00 USD variant priced at
2,654,700 Toman — exact to the rounding step. Audit rows confirmed the
variant change with before/after values, attributed to the acting admin.

Browser (Playwright, real admin login, port 3200): 13/13 checks — page and
status card render, master switch toggles AND persists across reload (server
round-trip), history tab renders filters/search/export, zero page errors.
Product modal: USD fields render, the third decimal is refused at the
keystroke, the settings link works.

Gates: 9/9 `run_gates.py` pass. Schema-sync gate passes (136 tables).
Frontend: 266 tests (+15 new), tsc clean, lint clean.

## Operational notes

- The sweep runs from Celery beat (`run-usd-rate-update`, every minute,
  interval-gated). Without a running beat+worker nothing updates
  automatically; the manual button works regardless.
- Configure from `/admin/currency`: set the manual rate (Toman) as the
  fallback, set the interval, set the rounding step. Amounts on the wire are
  integer Rial; the UI edits Toman.
- To put a variant under automatic pricing: set its USD price (and optional
  USD sale price) in the product editor. Clearing them removes it.
- Failed runs are recorded (status=failed with the error) and do not retry
  aggressively — the next interval tick tries again.
