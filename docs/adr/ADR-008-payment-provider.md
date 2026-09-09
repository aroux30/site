# ADR-008: Strategy Pattern for Payment Providers

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform must integrate with Iranian payment gateways to process online transactions. The Iranian payment ecosystem differs significantly from international providers: gateways use redirect-based flows (not direct API charges), have varying API designs, and their availability can be unpredictable. No single gateway is universally reliable.

Key payment providers in the Iranian market include Zarinpal, IDPay, and NextPay, among others. The platform must:

- Support multiple payment gateways simultaneously.
- Allow switching between gateways without modifying business logic.
- Enable adding new gateways with minimal code changes.
- Handle gateway-specific quirks (different callback formats, verification flows, error codes) behind a unified interface.
- Support automatic failover when a primary gateway is unavailable.

## Decision

We will implement payment gateway integration using the **Strategy pattern**, defining a common `PaymentProvider` interface that all gateway adapters implement.

### Design

```
PaymentProvider (Protocol / Abstract Base Class)
├── create_payment(amount, callback_url, metadata) -> PaymentRequest
├── verify_payment(authority, amount) -> PaymentResult
└── refund_payment(authority, amount) -> RefundResult

Concrete Implementations:
├── ZarinpalProvider
├── IDPayProvider
└── NextPayProvider
```

#### Interface Contract

- `create_payment()` initiates a payment and returns a redirect URL for the user.
- `verify_payment()` confirms a payment after the user returns from the gateway callback.
- `refund_payment()` initiates a refund for a previously verified payment.
- All methods return normalized result objects, abstracting gateway-specific response formats.

#### Provider Selection

- A `PaymentProviderFactory` selects the active provider based on configuration, allowing runtime switching via environment variables or admin settings.
- A `FallbackPaymentProvider` wraps multiple providers and attempts them in priority order, falling back to the next provider on connection failure or gateway error.

#### Transaction Logging

- Every payment interaction (request, callback, verification, refund) is logged to a `payment_transactions` table with the raw gateway request and response for auditing and debugging.

## Consequences

### Positive

- Adding a new payment gateway requires implementing only the `PaymentProvider` interface — no changes to order processing, checkout, or business logic.
- Gateway switching is a configuration change, not a code change, enabling rapid response to gateway outages.
- Automatic failover improves payment success rates and reduces revenue loss from gateway downtime.
- Normalized response objects keep business logic clean and gateway-agnostic.
- Raw transaction logging provides a complete audit trail for financial reconciliation and dispute resolution.

### Negative

- The abstraction may not perfectly capture all gateway-specific features. Some gateways offer unique capabilities (installment payments, wallet charging) that don't fit the common interface.
- Fallback logic introduces complexity: a payment started on one gateway cannot be verified on another. The system must track which gateway handled each transaction.
- Gateway-specific error handling must be mapped to common error types, which can lose diagnostic detail.

### Mitigations

- The `PaymentProvider` interface includes an `extras` dictionary for gateway-specific parameters and response data, allowing passthrough of unique features without breaking the common interface.
- The `payment_transactions` table records the provider identifier for each transaction, ensuring verification always routes to the correct gateway.
- Raw gateway responses are preserved alongside normalized results, so gateway-specific diagnostic information is always available for debugging.
- We implement comprehensive integration tests for each gateway adapter using recorded request/response fixtures.
