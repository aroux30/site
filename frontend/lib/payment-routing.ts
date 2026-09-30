/**
 * Payment-provider routing for checkout.
 *
 * Which provider needs which handling is a decision the checkout must get
 * exactly right: picking the wrong branch either skips payment creation
 * entirely (telling the customer the order succeeded when it is unpaid) or
 * redirects to a gateway URL that does not exist.
 */

/** How the checkout must complete a payment for a given provider. */
export type PaymentFlow =
  /** Provider issues a gateway URL; redirect the browser to it. */
  | "gateway"
  /** Offline bank transfer; the order stays unpaid until an admin reviews the slip. */
  | "card_transfer"
  /** No redirect — the server settles it in-page (wallet debit) or it is a dev mock. */
  | "in_page";

/**
 * Online providers whose payment is finalised at the gateway.
 *
 * `mock` is development-only but harmless to list: it is only ever returned by
 * `/payments/methods` when the environment explicitly enables it.
 */
const GATEWAY_PROVIDERS = new Set(["zarinpal", "idpay", "nextpay", "crypto"]);

/** Providers that settle without leaving the page. */
const IN_PAGE_PROVIDERS = new Set(["wallet", "mock"]);

/** Offline transfer providers that require an admin-reviewed receipt. */
const CARD_TRANSFER_PROVIDERS = new Set(["card_transfer"]);

/**
 * Classify a payment provider into the flow the checkout must run.
 *
 * Unknown providers fall through to `gateway`, matching the pre-existing
 * behaviour for newly added gateways. Card-to-card must never fall through:
 * it has no gateway and would otherwise be treated as "no payment needed".
 */
export function resolvePaymentFlow(provider: string): PaymentFlow {
  const key = provider.toLowerCase().trim();
  if (CARD_TRANSFER_PROVIDERS.has(key)) return "card_transfer";
  if (IN_PAGE_PROVIDERS.has(key)) return "in_page";
  if (GATEWAY_PROVIDERS.has(key)) return "gateway";
  return "gateway";
}

/**
 * True when the checkout must create a payment session (POST /payments).
 *
 * Every provider except card-to-card needs one — card-to-card is handled by
 * its own branch, which creates the session itself before showing the receipt
 * form. Returning false here for card-to-card keeps the two paths from both
 * creating a session and tripping the "active payment already exists" guard.
 */
export function requiresPaymentSession(provider: string): boolean {
  return resolvePaymentFlow(provider) !== "card_transfer";
}
