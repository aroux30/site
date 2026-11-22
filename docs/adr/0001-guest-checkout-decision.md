# ADR 0001 — Guest checkout: login stays required (Option A)

Status: Accepted — 2026-09-11
Deciders: Platform owner via audit roadmap TASK P4-01
Related: docs/ecommerce-fix-roadmap.md (ARCH-01), docs/integration-matrix.md (Journey C)

## Context

The storefront supports **guest carts** (session-based, `X-Session-ID` header)
so anonymous visitors can collect items before deciding anything. However the
checkout endpoints (`POST /checkout/create-order` and friends) require an
authenticated user (`Depends(get_current_user_id)`), so a guest cart can never
be converted to an order — Journey C (guest purchase) is impossible. The UI
previously implied guest checkout was possible, which is a dead end.

Two options were considered:

- **Option A (chosen):** keep login-required checkout. Iranian phone-OTP login
  is a low-friction step (a phone number + one SMS code), the platform already
  auto-creates the customer, and login-required checkout gives us an
  authenticated owner for every order, wallet, and RMA from the start — no
  nullable ownership, no order-claim flow, no guest data-protection surface.
- **Option B (rejected for now):** true guest checkout would require
  `orders.user_id` to become nullable (or a guest-identity table), capturing
  guest contact details, an order-claim flow at registration/login, and a
  data-protection review for orders belonging to no account. High complexity
  for marginal conversion gain given OTP friction is low.

## Decision

1. Checkout remains **login-required**.
2. Guest carts remain supported as **pre-login carts**: adding to cart while
   anonymous works exactly as today, and the existing cart-merge behavior
   carries the items into the authenticated session.
3. The checkout page already redirects anonymous users to
   `/login?redirect=/checkout` with Persian copy; no UI change is required
   beyond ensuring no copy promises guest ordering (verified — the checkout
   guard and cart-empty state both point to login/products).

## Consequences

- Journey C (guest purchase) is intentionally **not supported**; the
  integration matrix marks it as a product decision, not a defect.
- If conversion data later shows the login step is a major drop-off point,
  Option B can be revisited with the schema work described in the roadmap
  (`orders.user_id` nullable + claim flow). The cart session model does not
  block that path.
