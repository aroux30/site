# B2B / CRM / Vendors / Anti-fraud Removal (rmb2b1) — 2026-10-10

## Reason

The owner ordered the full removal of these subsystems. The store does not use
them. The removed subsystems are:

1. **B2B / reseller** — wholesale card purchases with instant PIN delivery,
   partner API keys (`X-API-KEY`), pre-paid credit.
2. **CRM** — the wholesale-inquiry pipeline. The owner confirmed: the whole
   module is B2B.
3. **Vendors** — the multi-vendor marketplace, plus the `vendor` RBAC role
   (the owner confirmed the role goes too).
4. **Anti-fraud / bank cards** — trust profiles, bank-card registration
   (Mana/Nehab), PAN matching, failed-attempts list, instant/delayed delivery.
5. **Pricing segments** — `WHOLESALE` and `B2B` left the customer-segment
   enum (the owner confirmed). PLATINUM now maps to GOLD.

## Data check before removal

All rows in the removed tables were test data. No real business data was lost.

| Table | Rows | What the rows were |
|---|---|---|
| `reseller_api_keys` | 22 | QA fixtures |
| `lead_inquiries` | 3 | Visual-test submissions |
| `user_trust_profiles` | 1 | Test row |
| `user_bank_cards` | 7 | One test PAN |
| `failed_attempts` | 194 | All LOGIN, none after 2026-09-20 |
| `vendors` | 1 | Browser-test store |
| `vendor_settlements` | 0 | Empty |
| `products.vendor_id` | 0 non-NULL | No product used a vendor |
| `product_variants.vendor_id` | 0 non-NULL | No variant used a vendor |
| `vendor` role | 0 holders | Only a `media:read` grant |
| `saved_reports` | 0 | No stored report used the removed type |

## What was removed

### Backend

- **Whole modules:** `crm`, `vendors`.
- **B2B code in orders:** `reseller_service.py`, `reseller_routes.py`,
  `reseller_models.py`, `schemas/reseller.py`.
- **Anti-fraud code in users:** `kyc_routes.py`, `kyc_service.py`,
  `bank_card_service.py`, `kyc_models.py`, `schemas/kyc.py`, and three admin
  service functions in `user_service.py`.
- **Auth:** the `_persist_failed_attempt` writer and its five call sites.
  The Redis brute-force lockout stays. It is the real gate.
- **Bank-card validators:** `IRANIAN_BANKS_BIN`, `validate_bank_card_luhn`,
  and `get_bank_name_by_bin` in `validation_utils.py` — their only caller was
  the removed `bank_card_service.py`. The frontend mirror (`SHETAB_BANKS`,
  `validateShetabCard` in `iranian-commerce.ts`) went the same way. The
  national-code functions stay — auth registration uses them. (Found in a
  cross-session review after the main removal.)
- **Catalog:** the `vendor_id` column, index, FK, and relationship on
  `products` and `product_variants`; the vendor re-exports.
- **Reporting:** the `vendor_settlement` report, the `vendor` sales group-by,
  the `vendor_id` filter, and the `vendor` entity in saved reports.
- **BI:** the `vendor_settlement` comparable report and the `vendor_id`
  parameter.
- **Search:** the vendor search entity and its collector.
- **Audit:** the `vendor` tracked entity and its registration.
- **Media:** the vendor usage buckets.
- **RBAC:** `crm:read`, `crm:write`, `vendors:read`, `vendors:write`, and the
  `vendor` role with its Casbin rows.
- **Pricing:** the `WHOLESALE` and `B2B` segment values.

### Frontend

- **Pages:** `/admin/b2b-reseller`, `/admin/crm`, `/admin/vendors`,
  `/admin/anti-fraud`, `/wholesale`, and the three `/account/seller` pages.
- **API clients:** `crm.ts`, `vendors.ts`, `seller.ts`, and the anti-fraud and
  vendor methods in `users.ts` and `admin.ts`.
- **Navigation:** four admin-nav entries, the footer wholesale link, the
  account-dashboard seller link, and the `wholesale` reserved root.
- **Reports/BI pages:** the settlement report type and the vendor options.
- **Users page:** the vendor role badge, filter option, and role dialog option.

### Database — migration `rmb2b1`

File: `backend/alembic/versions/2026_10_10_rmb2b1_remove_b2b_crm_vendors_antifraud.py`
(down_revision = `rmsub1`).

The migration drops seven tables, two columns, one role, and four
permissions. The downgrade recreates all of them with the exact live schema.
It pins the real permission and role IDs, so a downgrade restores the rows
the removed code referenced.

## What stayed

- Volume pricing (`price_tiers`, `calculate_dynamic_price`,
  `resolve_unit_price`) — retail cart, checkout, and the product page use it.
  Only the B2B call site left.
- Digital card allocation (`card_service.allocate_cards_for_order`) — the
  retail delivery path uses it.
- `orders:read` / `orders:write` — the whole orders module uses them.
- The Redis brute-force lockout — the real login/OTP gate.
- `validation_utils.py` — auth registration uses the national-code functions.
- `mask_card_pan` and `encrypt_pin` — payments and inventory use them.

## Verification

- 379/379 backend tests pass.
- 69/69 frontend tests pass (including the two-way admin-nav guard).
- `tsc` is clean.
- 9/9 project gates pass. The reassignment negative test passes (5/5).
- Downgrade then upgrade on the live database: everything returned and was
  removed again.
- Fresh chain on an empty database: 131 tables, head = `rmb2b1`. The live
  database also has 131 tables.
- Live backend probes: every removed path answers 404. The OpenAPI schema has
  510 paths and no removed path.
- Live frontend probes: the removed admin pages answer 307 (the auth
  redirect), the same as a control nonexistent path.

## Note

The reassignment verify script had a pre-existing break: it still passed the
removed `email` column to its user INSERT. The email feature was removed on
2026-10-07 (`rmemail1`). This removal fixed the script.
